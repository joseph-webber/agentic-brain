REST API - Agentic Brain
=======================

Quick OpenAPI examples and usage for the REST endpoints implemented in
src/agentic_brain/api/rest.py

Endpoints
---------

- POST /query
  - Description: Run a RAG query.
  - Body: {"question": "...", "top_k": 5}
  - Response: {"answer": "...", "sources": [{"id":"doc_1","score":0.5,"snippet":"..."}]}

- POST /index
  - Description: Index a document for retrieval.
  - Body: {"doc_id": "optional", "content": "...", "metadata": {...}}
  - Response: {"id": "doc_123", "status": "indexed"}

- GET /metrics
  - Description: Prometheus text exposition of internal metrics.
  - Response: text/plain in Prometheus exposition format.

- POST /graph/query
  - Description: Run a graph (Cypher) query. Placeholder for Neo4j integration.
  - Body: {"cypher": "MATCH (n) RETURN n LIMIT 1"}
  - Response: {"results": [...]}

- POST /evaluate
  - Description: RAGAS evaluation endpoint - compare candidate to reference.
  - Body: {"reference": "...", "candidate": "..."}
  - Response: {"score": 0.75, "reason": "..."}

- GET /config
  - Description: Retrieve runtime configuration (in-memory).
  - Response: {"values": {"key": "value"}}

- PUT /config
  - Description: Update runtime configuration (in-memory only).
  - Body: {"values": {"key": "value"}}
  - Response: Updated configuration.

Authentication
--------------

- API Key: provide header X-API-Key: <key> or query parameter ?api_key=<key>.
- Toggle authentication by setting environment variable AUTH_ENABLED=true and
  list valid keys in API_KEYS comma separated (e.g., API_KEYS=key1,key2).

Rate limiting
-------------

- Built-in simple rate limiter protects endpoints.
- Configure via environment variables:
  - REST_RATE_LIMIT_AUTH (default 100 requests/min)
  - REST_RATE_LIMIT_ANON (default 10 requests/min)

CLI
---

Start the server with the existing CLI entrypoint:

  agentic serve --port 8000

This uses uvicorn under the hood and mounts the full API including chat and
WebSocket endpoints.

Notes
-----

This implementation is intentionally lightweight and safe for unit tests. In
production you should replace the placeholder RAG/Neo4j logic with real
integrations, persist configuration to disk, and use a robust distributed rate
limiter if needed.
