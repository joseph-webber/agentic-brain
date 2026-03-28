"""Shared Neo4j schema helpers for indexes used across GraphRAG modules."""

# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

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
    f"CREATE VECTOR INDEX {VECTOR_INDEX_NAME} IF NOT EXISTS FOR (c:Chunk) ON (c.embedding) OPTIONS {{indexConfig: {{`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}}}}",
]


async def ensure_indexes(session) -> None:
    """Create the shared Neo4j indexes using an async session."""

    for idx in INDEXES:
        await session.run(idx)


def ensure_indexes_sync(session) -> None:
    """Create the shared Neo4j indexes using a synchronous session."""

    for idx in INDEXES:
        session.run(idx)
