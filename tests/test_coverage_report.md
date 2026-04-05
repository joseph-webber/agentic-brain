Coverage improvements report

- Added ~41 new tests across core and rag modules.
- Focus areas: core/rate_limiter, core/neo4j_utils, core/cache_manager, core/polymorphic, rag/graph

Key improvements:
- Rate limiter: exercised cooldowns, recording, learning and recommendations
- Neo4j utils: retried transient errors and honoured client errors (sync + async)
- CacheManager: serialization, corrupted payload handling, and session interactions
- PolymorphicBrain: persona detection, profile adaptation, prompt modifier generation
- GraphRAG: embedding validation, chunking, and hybrid retrieval fusion logic

Run pytest to confirm full suite: pytest -q agentic-brain/tests
