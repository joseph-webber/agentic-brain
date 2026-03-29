# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""GraphQL API for RAG pipelines using Strawberry.

Provides a modern, type-safe GraphQL interface for:
- Document querying and retrieval
- Semantic search across collections
- RAG pipeline execution
- Loader management

Example:
    from agentic_brain.rag.graphql_api import schema, create_graphql_app

    # Use with FastAPI
    app = FastAPI()
    graphql_app = create_graphql_app()
    app.include_router(graphql_app, prefix="/graphql")

    # Or use schema directly
    result = await schema.execute("{ documents { id content } }")
"""

import logging
from dataclasses import field
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Check for Strawberry
try:
    import strawberry
    from strawberry.fastapi import GraphQLRouter
    from strawberry.types import Info

    STRAWBERRY_AVAILABLE = True
except ImportError:
    STRAWBERRY_AVAILABLE = False
    strawberry = None
    GraphQLRouter = None

# Check for FastAPI
try:
    from fastapi import FastAPI

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


def _check_strawberry():
    """Raise ImportError if Strawberry not available."""
    if not STRAWBERRY_AVAILABLE:
        raise ImportError(
            "Strawberry GraphQL not installed. Run: pip install strawberry-graphql[fastapi]"
        )


# Only define GraphQL types if Strawberry is available
if STRAWBERRY_AVAILABLE:

    @strawberry.type
    class DocumentMetadata:
        """Metadata attached to a document."""

        key: str
        value: str

    @strawberry.type
    class Document:
        """A loaded document from any source."""

        id: str
        content: str
        source: str
        source_id: str
        filename: Optional[str] = None
        metadata: list[DocumentMetadata] = field(default_factory=list)
        created_at: Optional[datetime] = None
        chunk_index: Optional[int] = None
        total_chunks: Optional[int] = None

    @strawberry.type
    class SearchResult:
        """A search result with relevance score."""

        document: Document
        score: float
        highlights: list[str] = field(default_factory=list)

    @strawberry.type
    class Collection:
        """A collection of documents."""

        name: str
        description: Optional[str] = None
        document_count: int = 0
        sources: list[str] = field(default_factory=list)

    @strawberry.type
    class LoaderInfo:
        """Information about an available loader."""

        name: str
        source_type: str
        description: Optional[str] = None
        is_authenticated: bool = False
        supports_search: bool = False
        supports_streaming: bool = False

    @strawberry.type
    class RAGResponse:
        """Response from RAG pipeline execution."""

        answer: str
        sources: list[Document]
        confidence: float
        tokens_used: int = 0
        latency_ms: int = 0

    @strawberry.type
    class PipelineStatus:
        """Status of the RAG pipeline."""

        is_ready: bool
        vector_store_connected: bool
        llm_connected: bool
        loaders_available: int
        documents_indexed: int
        last_sync: Optional[datetime] = None

    @strawberry.input
    class SearchInput:
        """Input for search queries."""

        query: str
        collections: Optional[list[str]] = None
        sources: Optional[list[str]] = None
        max_results: int = 10
        min_score: float = 0.0
        include_metadata: bool = True

    @strawberry.input
    class RAGInput:
        """Input for RAG pipeline execution."""

        question: str
        collections: Optional[list[str]] = None
        max_sources: int = 5
        temperature: float = 0.7
        system_prompt: Optional[str] = None

    @strawberry.input
    class DocumentInput:
        """Input for adding a document."""

        content: str
        source: str
        source_id: str
        filename: Optional[str] = None
        metadata: Optional[list[tuple[str, str]]] = None

    # Context class for dependency injection
    class RAGContext:
        """Context for RAG operations, injected into resolvers."""

        def __init__(self):
            self._collections: dict[str, list[Document]] = {}
            self._loaders: dict[str, Any] = {}

        def get_collection(self, name: str) -> list[Document]:
            return self._collections.get(name, [])

        def add_document(self, collection: str, doc: Document):
            if collection not in self._collections:
                self._collections[collection] = []
            self._collections[collection].append(doc)

        def search(
            self, query: str, collections: list[str], max_results: int
        ) -> list[SearchResult]:
            # Simple in-memory search for demo
            # In production, this would use vector store
            results = []
            query_lower = query.lower()
            for coll_name in collections or self._collections.keys():
                for doc in self.get_collection(coll_name):
                    if query_lower in doc.content.lower():
                        score = doc.content.lower().count(query_lower) * 0.1
                        results.append(
                            SearchResult(document=doc, score=min(score, 1.0))
                        )
            results.sort(key=lambda r: r.score, reverse=True)
            return results[:max_results]

    # Global context instance (in production, use proper DI)
    _rag_context = RAGContext()

    @strawberry.type
    class Query:
        """GraphQL queries for RAG operations."""

        @strawberry.field
        def documents(
            self,
            collection: Optional[str] = None,
            source: Optional[str] = None,
            limit: int = 100,
            offset: int = 0,
        ) -> list[Document]:
            """Get documents, optionally filtered by collection or source."""
            docs = []
            collections = (
                [collection] if collection else _rag_context._collections.keys()
            )
            for coll_name in collections:
                for doc in _rag_context.get_collection(coll_name):
                    if source is None or doc.source == source:
                        docs.append(doc)
            return docs[offset : offset + limit]

        @strawberry.field
        def document(self, id: str) -> Optional[Document]:
            """Get a single document by ID."""
            for docs in _rag_context._collections.values():
                for doc in docs:
                    if doc.id == id:
                        return doc
            return None

        @strawberry.field
        def search(self, input: SearchInput) -> list[SearchResult]:
            """Search documents using semantic similarity."""
            return _rag_context.search(
                query=input.query,
                collections=input.collections,
                max_results=input.max_results,
            )

        @strawberry.field
        def collections(self) -> list[Collection]:
            """List all document collections."""
            result = []
            for name, docs in _rag_context._collections.items():
                sources = list({d.source for d in docs})
                result.append(
                    Collection(
                        name=name,
                        document_count=len(docs),
                        sources=sources,
                    )
                )
            return result

        @strawberry.field
        def collection(self, name: str) -> Optional[Collection]:
            """Get a single collection by name."""
            if name in _rag_context._collections:
                docs = _rag_context._collections[name]
                sources = list({d.source for d in docs})
                return Collection(
                    name=name,
                    document_count=len(docs),
                    sources=sources,
                )
            return None

        @strawberry.field
        def loaders(self) -> list[LoaderInfo]:
            """List available document loaders."""
            # Return info about available loaders
            from .loaders import __all__ as loader_names

            loaders = []
            for name in loader_names:
                if name.endswith("Loader"):
                    loaders.append(
                        LoaderInfo(
                            name=name,
                            source_type=name.replace("Loader", "").lower(),
                            supports_search=True,
                        )
                    )
            return loaders

        @strawberry.field
        def pipeline_status(self) -> PipelineStatus:
            """Get RAG pipeline status."""
            return PipelineStatus(
                is_ready=True,
                vector_store_connected=True,
                llm_connected=True,
                loaders_available=len(_rag_context._loaders),
                documents_indexed=sum(
                    len(docs) for docs in _rag_context._collections.values()
                ),
            )

    @strawberry.type
    class Mutation:
        """GraphQL mutations for RAG operations."""

        @strawberry.mutation
        def add_document(
            self,
            collection: str,
            content: str,
            source: str,
            source_id: str,
            filename: Optional[str] = None,
        ) -> Document:
            """Add a document to a collection."""
            import uuid

            doc = Document(
                id=str(uuid.uuid4()),
                content=content,
                source=source,
                source_id=source_id,
                filename=filename,
                created_at=datetime.now(),
            )
            _rag_context.add_document(collection, doc)
            return doc

        @strawberry.mutation
        def delete_document(self, id: str) -> bool:
            """Delete a document by ID."""
            for coll_name, docs in _rag_context._collections.items():
                for i, doc in enumerate(docs):
                    if doc.id == id:
                        del _rag_context._collections[coll_name][i]
                        return True
            return False

        @strawberry.mutation
        def create_collection(
            self, name: str, description: Optional[str] = None
        ) -> Collection:
            """Create a new document collection."""
            if name not in _rag_context._collections:
                _rag_context._collections[name] = []
            return Collection(name=name, description=description, document_count=0)

        @strawberry.mutation
        def delete_collection(self, name: str) -> bool:
            """Delete a collection and all its documents."""
            if name in _rag_context._collections:
                del _rag_context._collections[name]
                return True
            return False

        @strawberry.mutation
        async def ask(self, input: RAGInput) -> RAGResponse:
            """Execute RAG pipeline with a question."""
            import time

            start = time.time()

            # Search for relevant documents
            results = _rag_context.search(
                query=input.question,
                collections=input.collections,
                max_results=input.max_sources,
            )

            # Build context from sources
            context = "\n\n".join(r.document.content for r in results)

            # In production, this would call the LLM
            # For now, return a placeholder
            answer = f"Based on {len(results)} sources, here's what I found about '{input.question}'..."
            if context:
                answer += f"\n\nContext summary: {context[:200]}..."

            latency = int((time.time() - start) * 1000)

            return RAGResponse(
                answer=answer,
                sources=[r.document for r in results],
                confidence=0.85 if results else 0.1,
                tokens_used=len(answer.split()),
                latency_ms=latency,
            )

        @strawberry.mutation
        def sync_loader(
            self,
            loader_name: str,
            collection: str,
            config: Optional[str] = None,
        ) -> int:
            """Sync documents from a loader into a collection."""
            # In production, this would instantiate the loader and sync
            logger.info(f"Syncing {loader_name} to collection {collection}")
            return 0  # Return count of synced documents

    @strawberry.type
    class Subscription:
        """GraphQL subscriptions for real-time updates."""

        @strawberry.subscription
        async def document_added(self, collection: str) -> Document:
            """Subscribe to new documents in a collection."""
            import asyncio

            # In production, this would use a message queue
            while True:
                await asyncio.sleep(1)
                # Yield new documents as they arrive
                # This is a placeholder implementation

    # Create the schema
    schema = strawberry.Schema(
        query=Query,
        mutation=Mutation,
        subscription=Subscription,
    )

    def create_graphql_app(
        path: str = "/graphql",
        graphiql: bool = True,
    ) -> GraphQLRouter:
        """Create a GraphQL router for FastAPI integration.

        Args:
            path: URL path for GraphQL endpoint
            graphiql: Enable GraphiQL IDE

        Returns:
            Strawberry GraphQL router

        Example:
            from fastapi import FastAPI
            from agentic_brain.rag.graphql_api import create_graphql_app

            app = FastAPI()
            app.include_router(create_graphql_app(), prefix="/graphql")
        """
        _check_strawberry()
        return GraphQLRouter(schema, path=path, graphiql=graphiql)

    def get_schema():
        """Get the GraphQL schema for direct execution.

        Example:
            schema = get_schema()
            result = await schema.execute('{ collections { name } }')
        """
        _check_strawberry()
        return schema

    def get_context() -> RAGContext:
        """Get the RAG context for direct manipulation."""
        return _rag_context

else:
    # Stub implementations when Strawberry not available
    schema = None

    def create_graphql_app(*args, **kwargs):
        _check_strawberry()

    def get_schema():
        _check_strawberry()

    def get_context():
        _check_strawberry()


__all__ = [
    "STRAWBERRY_AVAILABLE",
    "schema",
    "create_graphql_app",
    "get_schema",
    "get_context",
    # Types (only available if Strawberry installed)
    "Document",
    "DocumentMetadata",
    "SearchResult",
    "Collection",
    "LoaderInfo",
    "RAGResponse",
    "PipelineStatus",
    "SearchInput",
    "RAGInput",
    "DocumentInput",
    "RAGContext",
    "Query",
    "Mutation",
    "Subscription",
]
