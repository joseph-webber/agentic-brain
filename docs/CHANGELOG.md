# Documentation Changelog

Documentation-facing release notes for the current Agentic Brain docs set.

For older package history, see the root [CHANGELOG.md](../CHANGELOG.md).

## [2.15.0] - 2026-03-28

### Added

- New [GraphRAG guide](GRAPHRAG.md) covering:
  - `KnowledgeExtractor` graph extraction and safe Text2Cypher
  - `GraphRAG` search strategies (`vector`, `graph`, `hybrid`, `community`, `multi_hop`)
  - `EnhancedGraphRAG` Neo4j vector indexing and reciprocal-rank-fusion retrieval
  - Neo4j GDS community detection workflows using **Leiden**
  - embedding integration patterns and configuration reference
- Expanded integration docs for the built-in GraphRAG architecture and hybrid vector + graph retrieval
- README architecture notes describing the GraphRAG data flow, hybrid retrieval stages, and community-expansion step

### Changed

- GraphRAG documentation now describes the **layered architecture** across:
  - `agentic_brain.rag.graphrag`
  - `agentic_brain.rag.graph_rag`
  - `agentic_brain.rag.graph`
- README feature highlights now emphasize:
  - hybrid vector + graph retrieval
  - safe natural-language graph querying
  - community-aware retrieval workflows
  - embedding-aware Neo4j integrations
- Documentation now points readers to a dedicated GraphRAG guide instead of scattering details across multiple files

### Fixed

- Clarified that core GraphRAG extraction is built in and does **not** require `neo4j-graphrag` for the standard workflow
- Documented the safe fallback behaviour when LLM-generated Cypher is rejected or graph extraction fails
- Documented the current production retrieval path in `EnhancedGraphRAG`, including vector-index fallback to text search
- Documented how community detection fits into the release even when executed through Neo4j GDS rather than an inline helper
- Captured the related router release fixes that ship alongside this documentation refresh:
  - normalized multi-provider `messages` handling
  - friendly model alias resolution
  - rate-limit backoff and ordered fallback routing
  - per-request token and cost tracking
