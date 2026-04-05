# SPDX-License-Identifier: Apache-2.0
"""Shared Neo4j schema helpers for indexes used across GraphRAG modules.

Maintains a canonical set of indexes for fulltext search, range filtering,
and vector similarity matching used by RAG and entity extraction.
"""

# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

from __future__ import annotations

VECTOR_INDEX_NAME = "chunk_embeddings"

INDEXES = [
    # Fulltext indexes for fast text search
    "CREATE FULLTEXT INDEX entity_fulltext IF NOT EXISTS FOR (e:Entity) ON EACH [e.name, e.description]",
    "CREATE FULLTEXT INDEX chunk_fulltext IF NOT EXISTS FOR (c:Chunk) ON EACH [c.content]",
    "CREATE FULLTEXT INDEX document_fulltext IF NOT EXISTS FOR (d:Document) ON EACH [d.content, d.title]",
    # Range indexes for filtering
    "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type)",
    "CREATE INDEX chunk_doc_id IF NOT EXISTS FOR (c:Chunk) ON (c.document_id)",
    "CREATE INDEX document_timestamp IF NOT EXISTS FOR (d:Document) ON (d.timestamp)",
    # Vector index (standardized name)
    "CREATE VECTOR INDEX "
    + VECTOR_INDEX_NAME
    + " IF NOT EXISTS FOR (c:Chunk) ON (c.embedding) OPTIONS "
    + "{indexConfig: {`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}}",
]


async def ensure_indexes(session) -> None:
    """Create the shared Neo4j indexes using an async session.

    Idempotent: safe to call multiple times. Uses IF NOT EXISTS clauses
    to avoid errors if indexes already exist.

    Args:
        session: Async Neo4j session from async_get_session().

    Raises:
        ServiceUnavailable: If Neo4j connection is unavailable.
    """

    for idx in INDEXES:
        await session.run(idx)


def ensure_indexes_sync(session) -> None:
    """Create the shared Neo4j indexes using a synchronous session.

    Synchronous version of ensure_indexes for blocking contexts.
    Idempotent: safe to call multiple times.

    Args:
        session: Sync Neo4j session from get_session().

    Raises:
        ServiceUnavailable: If Neo4j connection is unavailable.
    """

    for idx in INDEXES:
        session.run(idx)
