# Integration Testing

Run the real integration suite with:

```bash
pytest tests/integration -m integration
```

Component markers:

- `rag` – document ingestion, retrieval, caching, evaluation
- `graph` – graph indexing and graph queries
- `llm` – provider dispatch, retries, fallback, usage tracking
- `embeddings` – embedding generation and similarity checks
- `api` – FastAPI e2e session and chat flows

Optional live services:

- Neo4j: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- Redis: `REDIS_HOST`, `REDIS_PORT`
- CI gating: `CI_RUN_INTEGRATION=1`

The integration suite prefers real code paths and HTTP I/O. When external
services are unavailable, tests fall back to deterministic local fixtures so the
workflow still exercises the production modules.

