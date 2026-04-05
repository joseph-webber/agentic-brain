Session storage performance improvements

This document summarizes the recent improvements made to Neo4j-backed session storage in agentic-brain.

Goals
- Reuse Neo4j connections via the shared pool
- Batch message inserts to minimize round-trips
- Lazy-load session data into memory only when needed
- Support pagination for message retrieval
- Create targeted indexes for faster queries

What changed
1. Connection pooling
- Core driver and pool utilities (agentic_brain.core.neo4j_pool) are used consistently.
- Backends use get_session() context manager so driver-managed pooling is reused.

2. Batch operations
- Neo4jSessionBackend.store_messages_bulk(messages) added. Uses UNWIND to create messages in one write.
- ConversationMemory.add_messages_batch(messages) added to batch insert messages for a session.

3. Lazy loading
- Sessions are no longer preloaded from storage when created. Messages are only fetched when get_messages or related APIs are called.
- Session.get_messages will request pages on demand (backend-side) to avoid loading entire history.

4. Pagination
- Neo4jSessionBackend.get_messages supports page and page_size (SKIP/LIMIT) and optional include_content flag.
- ConversationMemory.get_conversation_history supports page/page_size and since filters.
- SQLite fallback supports page/page_size where applicable.

5. Indexing
- Additional indices (message_content, message_timestamp, message_importance, session_timestamp, entity_type) are created in initialization.
- Full-text / content indexes are created where supported to accelerate searches.

Testing
- A new test suite tests/test_memory/test_neo4j_optimization.py mocks the Neo4j session and validates batching, pagination, lazy loading behavior, and index creation. Tests run without a real Neo4j instance.

Operational notes
- For best production performance, configure the Neo4j driver pool via environment variables (NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_POOL_SIZE).
- Monitor pool metrics and tune max connections according to workload.
- Use batch inserts during high-throughput ingestion to reduce write amplification.

