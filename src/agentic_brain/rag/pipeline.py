# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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

"""
RAG Pipeline - Complete retrieval-augmented generation.

Combines retrieval, context building, and LLM generation
into a single easy-to-use pipeline.

For enterprise features (multi-tenant, cross-encoder reranking,
streaming responses, MLX acceleration), see brain-core.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from collections.abc import Generator
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from .embeddings import EmbeddingProvider, get_embeddings
from .graph_traversal import (
    GraphContext,
    GraphNode,
    GraphTraversalRetriever,
    TraversalStrategy,
)
from .retriever import RetrievedChunk, Retriever

if TYPE_CHECKING:
    from .loaders.base import BaseLoader
    from .store import Document, DocumentStore

logger = logging.getLogger(__name__)


# Response cache
CACHE_DIR = Path.home() / ".agentic_brain" / "rag_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


LOCAL_EXTENSION_LOADERS: dict[str, str] = {
    ".txt": "text",
    ".text": "text",
    ".log": "text",
    ".md": "markdown",
    ".markdown": "markdown",
    ".mdown": "markdown",
    ".mkd": "markdown",
    ".json": "json",
    ".jsonl": "jsonl",
    ".ndjson": "jsonl",
    ".csv": "csv",
    ".tsv": "csv",
    ".xls": "excel",
    ".xlsx": "excel",
    ".xlsm": "excel",
    ".pdf": "pdf",
    ".doc": "docx",
    ".docx": "docx",
    ".html": "html",
    ".htm": "html",
}


@dataclass
class RAGResult:
    """Result from RAG query."""

    query: str
    answer: str
    sources: list[RetrievedChunk]
    confidence: float
    model: str
    cached: bool = False
    generation_time_ms: float = 0

    @property
    def has_sources(self) -> bool:
        return len(self.sources) > 0

    @property
    def confidence_level(self) -> str:
        if self.confidence >= 0.8:
            return "high"
        elif self.confidence >= 0.5:
            return "medium"
        elif self.confidence >= 0.3:
            return "low"
        return "uncertain"

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "answer": self.answer,
            "sources": [
                {"content": s.content[:200], "source": s.source, "score": s.score}
                for s in self.sources
            ],
            "confidence": self.confidence,
            "confidence_level": self.confidence_level,
            "model": self.model,
        }

    def format_with_citations(self) -> str:
        """Format answer with source citations."""
        lines = [self.answer, "", "---", "Sources:"]
        for i, source in enumerate(self.sources[:3], 1):
            lines.append(f"[{i}] {source.source} (confidence: {source.confidence})")
        return "\n".join(lines)


@dataclass
class GraphSearchResult:
    """Result from a graph search query."""

    query: str
    nodes: list[GraphNode]
    edges: list[dict[str, Any]]
    relevance_scores: dict[str, float]

    @property
    def has_results(self) -> bool:
        return bool(self.nodes)


@dataclass
class GraphQueryResult:
    """Result from a natural language graph query."""

    query: str
    answer: str
    sources: list[GraphNode]
    graph_context: GraphContext


@dataclass
class IngestResult:
    """Summary of an ingestion run."""

    documents_processed: int
    chunks_created: int
    errors: list[str]
    duration_seconds: float

    @property
    def success(self) -> bool:
        return not self.errors


class RAGPipeline:
    """
    Complete RAG pipeline.

    Usage:
        # Simple usage
        rag = RAGPipeline()
        result = rag.query("What is the deployment process?")
        print(result.answer)

        # With Neo4j
        rag = RAGPipeline(
            neo4j_uri="bolt://localhost:7687",
            neo4j_password="your-password-here"
        )
        result = rag.query("Status of project X?", sources=["JiraTicket"])

        # With specific LLM
        rag = RAGPipeline(llm_provider="ollama", llm_model="llama3.1:8b")
    """

    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_user: str = "neo4j",
        neo4j_password: Optional[str] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        llm_provider: str = "ollama",
        llm_model: str = "llama3.1:8b",
        llm_base_url: Optional[str] = None,
        cache_ttl_hours: int = 4,
        document_store: Optional["DocumentStore"] = None,
    ):
        embedding_provider = embedding_provider or get_embeddings()
        self._document_store = document_store
        self.retriever = Retriever(
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            embedding_provider=embedding_provider,
            document_store=self._document_store,
        )
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.llm_base_url = llm_base_url or os.getenv(
            "OLLAMA_HOST", "http://localhost:11434"
        )
        self.timeout = int(os.getenv("LLM_TIMEOUT", "60"))
        self.cache_ttl_hours = cache_ttl_hours

    def _cache_key(self, query: str, sources: list[str]) -> str:
        """Generate cache key."""
        key_data = f"{query}:{sorted(sources)}:{self.llm_model}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]

    def _get_cached(self, cache_key: str) -> Optional[RAGResult]:
        """Get cached result if valid."""
        cache_file = CACHE_DIR / f"{cache_key}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text())
                cached_time = datetime.fromisoformat(data["timestamp"])
                age_hours = (datetime.now() - cached_time).total_seconds() / 3600

                if age_hours < self.cache_ttl_hours:
                    return RAGResult(
                        query=data["query"],
                        answer=data["answer"],
                        sources=[],  # Don't cache full sources
                        confidence=data["confidence"],
                        model=data["model"],
                        cached=True,
                    )
            except (OSError, json.JSONDecodeError, ValueError, KeyError) as e:
                # json.JSONDecodeError: corrupted cache file
                # ValueError: invalid datetime format
                # KeyError: missing expected field
                # IOError: file read error
                logger.debug(f"Cache read failed: {e}")
                pass
        return None

    def _set_cached(self, cache_key: str, result: RAGResult) -> None:
        """Cache a result."""
        cache_file = CACHE_DIR / f"{cache_key}.json"
        data = {
            "query": result.query,
            "answer": result.answer,
            "confidence": result.confidence,
            "model": result.model,
            "timestamp": datetime.now().isoformat(),
        }
        cache_file.write_text(json.dumps(data))

    def _build_context(
        self, chunks: list[RetrievedChunk], max_tokens: int = 3000
    ) -> str:
        """Build context string from chunks."""
        context_parts = []
        total_chars = 0
        max_chars = max_tokens * 4  # Rough token estimate

        for chunk in chunks:
            chunk_context = chunk.to_context()
            if total_chars + len(chunk_context) > max_chars:
                break
            context_parts.append(chunk_context)
            total_chars += len(chunk_context)

        return "\n\n".join(context_parts)

    def _assemble_context(
        self, chunks: list[RetrievedChunk], max_tokens: int = 3000
    ) -> str:
        """Backward-compatible alias used by CI tests."""
        return self._build_context(chunks, max_tokens=max_tokens)

    def _generate_ollama(self, prompt: str, context: str) -> str:
        """Generate response using Ollama."""
        import requests

        system = """You are a helpful assistant. Answer based on the provided context.
If the context doesn't contain relevant information, say so.
Be concise and accurate. Cite sources when possible."""

        full_prompt = f"""Context:
{context}

Question: {prompt}

Answer:"""

        response = requests.post(
            f"{self.llm_base_url}/api/generate",
            json={
                "model": self.llm_model,
                "prompt": full_prompt,
                "system": system,
                "stream": False,
                "options": {"temperature": 0.3},
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()["response"]

    def _generate_openai(self, prompt: str, context: str) -> str:
        """Generate response using OpenAI."""
        import requests

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY required")

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.llm_model,
                "messages": [
                    {
                        "role": "system",
                        "content": "Answer based on the provided context. Be concise and accurate.",
                    },
                    {
                        "role": "user",
                        "content": f"Context:\n{context}\n\nQuestion: {prompt}",
                    },
                ],
                "temperature": 0.3,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def _generate(self, prompt: str, context: str) -> str:
        """Generate response using configured LLM."""
        if self.llm_provider == "ollama":
            return self._generate_ollama(prompt, context)
        elif self.llm_provider == "openai":
            return self._generate_openai(prompt, context)
        else:
            raise ValueError(f"Unknown LLM provider: {self.llm_provider}")

    def _build_graph_retriever(self) -> GraphTraversalRetriever:
        """Construct a graph traversal retriever using pipeline settings."""
        driver = self.retriever._get_driver()
        return GraphTraversalRetriever(driver, embeddings=self.retriever.embeddings)

    def _infer_graph_hints(
        self, query: str
    ) -> tuple[list[str] | None, list[str] | None, TraversalStrategy]:
        """Infer graph labels, relationships, and traversal strategy from query."""
        query_lower = query.lower()

        label_hints = {
            "person": ["Person"],
            "people": ["Person"],
            "owner": ["Person"],
            "team": ["Team"],
            "project": ["Project"],
            "service": ["Service"],
            "system": ["System"],
            "ticket": ["Ticket", "Issue"],
            "document": ["Document"],
            "knowledge": ["Knowledge"],
            "memory": ["Memory"],
        }
        relationship_hints = {
            "depends": ["DEPENDS_ON"],
            "dependency": ["DEPENDS_ON"],
            "relates": ["RELATED_TO"],
            "related": ["RELATED_TO"],
            "mentions": ["MENTIONS"],
            "references": ["REFERENCES"],
            "part of": ["PART_OF"],
            "belongs to": ["PART_OF"],
            "works on": ["WORKS_ON"],
            "owns": ["OWNED_BY"],
            "owned by": ["OWNED_BY"],
        }

        labels: set[str] = set()
        for token, hint_labels in label_hints.items():
            if token in query_lower:
                labels.update(hint_labels)

        relationships: list[str] = []
        for token, hint_relationships in relationship_hints.items():
            if token in query_lower:
                relationships.extend(hint_relationships)

        strategy = TraversalStrategy.HYBRID
        if any(token in query_lower for token in ["path", "chain", "lineage"]):
            strategy = TraversalStrategy.DEPTH_FIRST
        elif any(
            token in query_lower for token in ["neighbors", "related", "connected"]
        ):
            strategy = TraversalStrategy.BREADTH_FIRST

        return list(labels) or None, relationships or None, strategy

    def query(
        self,
        query: str,
        k: int = 5,
        sources: Optional[list[str]] = None,
        use_cache: bool = True,
        min_score: float = 0.3,
    ) -> RAGResult:
        """
        Query the RAG pipeline.

        Args:
            query: Question to answer
            k: Number of documents to retrieve
            sources: Specific sources to search
            use_cache: Whether to use cached responses
            min_score: Minimum relevance score

        Returns:
            RAGResult with answer and sources
        """
        start = time.time()

        sources = sources or ["Document", "Memory", "Knowledge"]

        # Cache is disabled by default in CI to keep results deterministic.
        cache_enabled = use_cache and os.getenv(
            "RAG_CACHE_ENABLED", "false"
        ).lower() in (
            "1",
            "true",
            "yes",
        )
        if cache_enabled:
            cache_key = self._cache_key(query, sources)
            cached = self._get_cached(cache_key)
            if cached:
                return cached

        # Retrieve relevant documents
        chunks = self.retriever.retrieve(query, top_k=k, sources=sources)
        if not isinstance(chunks, list) or not chunks:
            try:
                chunks = self.retriever.search(query, k=k, sources=sources)
            except TypeError:
                chunks = self.retriever.search(query, k=k)
        chunks = [c for c in chunks if c.score >= min_score]

        # Build context
        context = self._build_context(chunks)

        # Generate response
        if not context:
            answer = "I don't have enough information to answer that question."
            confidence = 0.0
        else:
            answer = self._generate(query, context)
            # Confidence based on source scores
            confidence = sum(c.score for c in chunks) / len(chunks) if chunks else 0.0

        elapsed = (time.time() - start) * 1000

        result = RAGResult(
            query=query,
            answer=answer,
            sources=chunks,
            confidence=confidence,
            model=f"{self.llm_provider}/{self.llm_model}",
            generation_time_ms=elapsed,
        )

        # Cache result
        if cache_enabled and context:
            self._set_cached(cache_key, result)

        return result

    async def graph_search(self, query: str, **kwargs: Any) -> GraphSearchResult:
        """Search using knowledge graph relationships."""
        start_labels = kwargs.get("start_labels") or kwargs.get("labels")
        relationship_types = kwargs.get("relationship_types") or kwargs.get(
            "relationships"
        )
        max_depth = int(kwargs.get("max_depth", 2))
        limit = int(kwargs.get("limit", kwargs.get("k", 20)))
        strategy = kwargs.get("strategy", TraversalStrategy.HYBRID)

        inferred_labels, inferred_relationships, inferred_strategy = (
            self._infer_graph_hints(query)
        )
        if start_labels is None:
            start_labels = inferred_labels
        if relationship_types is None:
            relationship_types = inferred_relationships
        if "strategy" not in kwargs:
            strategy = inferred_strategy

        try:
            graph_retriever = self._build_graph_retriever()
            context = await asyncio.to_thread(
                graph_retriever.retrieve,
                query=query,
                start_labels=start_labels,
                relationship_types=relationship_types,
                max_depth=max_depth,
                limit=limit,
                strategy=strategy,
            )
        except Exception as e:
            logger.warning(f"Graph search unavailable: {e}")
            return GraphSearchResult(
                query=query,
                nodes=[],
                edges=[],
                relevance_scores={},
            )

        nodes = context.root_nodes + context.related_nodes
        relevance_scores: dict[str, float] = {}
        for index, node in enumerate(nodes):
            node_id = node.id if node.id is not None else f"node_{index}"
            relevance_scores[str(node_id)] = node.score

        return GraphSearchResult(
            query=query,
            nodes=nodes,
            edges=context.relationships,
            relevance_scores=relevance_scores,
        )

    async def graph_query(self, query: str, **kwargs: Any) -> GraphQueryResult:
        """Natural language query over the knowledge graph."""
        start_labels = kwargs.get("start_labels") or kwargs.get("labels")
        relationship_types = kwargs.get("relationship_types") or kwargs.get(
            "relationships"
        )
        max_depth = int(kwargs.get("max_depth", 2))
        limit = int(kwargs.get("limit", kwargs.get("k", 20)))
        max_nodes = int(kwargs.get("max_nodes", 10))
        strategy = kwargs.get("strategy")

        inferred_labels, inferred_relationships, inferred_strategy = (
            self._infer_graph_hints(query)
        )
        if start_labels is None:
            start_labels = inferred_labels
        if relationship_types is None:
            relationship_types = inferred_relationships
        if strategy is None:
            strategy = inferred_strategy

        try:
            graph_retriever = self._build_graph_retriever()
            context = await asyncio.to_thread(
                graph_retriever.retrieve,
                query=query,
                start_labels=start_labels,
                relationship_types=relationship_types,
                max_depth=max_depth,
                limit=limit,
                strategy=strategy,
            )
        except Exception as e:
            logger.warning(f"Graph query unavailable: {e}")
            empty_context = GraphContext(
                query=query,
                root_nodes=[],
                related_nodes=[],
                relationships=[],
                total_nodes=0,
                max_depth=0,
            )
            return GraphQueryResult(
                query=query,
                answer="I couldn't access the knowledge graph for this query.",
                sources=[],
                graph_context=empty_context,
            )

        sources = context.root_nodes + context.related_nodes
        if sources:
            graph_context_text = context.as_context_string(max_nodes=max_nodes)
            try:
                answer = await asyncio.to_thread(
                    self._generate, query, graph_context_text
                )
            except Exception as e:
                logger.warning(f"Graph query generation failed: {e}")
                answer = (
                    "I found relevant graph context but could not generate an answer."
                )
        else:
            answer = "I couldn't find relevant graph context to answer that question."

        return GraphQueryResult(
            query=query,
            answer=answer,
            sources=sources,
            graph_context=context,
        )

    def add_document(
        self,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
        doc_id: Optional[str] = None,
    ) -> "Document":
        """
        Add a document to the store.

        Args:
            content: Document content
            metadata: Optional metadata
            doc_id: Optional document ID (auto-generated if not provided)

        Returns:
            Document object with chunks

        Raises:
            RuntimeError: If no document store is configured
        """
        if self._document_store is None:
            raise RuntimeError(
                "No document store configured. Pass document_store to RAGPipeline constructor."
            )

        return self._document_store.add(content, metadata, doc_id)

    def list_documents(self, limit: int = 100) -> list["Document"]:
        """
        List documents in the store.

        Args:
            limit: Maximum number of documents to return

        Returns:
            List of Document objects
        """
        if self._document_store is None:
            return []

        return self._document_store.list(limit=limit)

    def get_stats(self) -> dict[str, Any]:
        """
        Get pipeline statistics.

        Returns:
            Dictionary with statistics about the pipeline and document store
        """
        stats = {
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "cache_ttl_hours": self.cache_ttl_hours,
        }

        if self._document_store is not None:
            store_stats = self._document_store.stats()
            stats.update(store_stats)
        else:
            stats["document_count"] = 0
            stats["total_chunks"] = 0

        return stats

    def query_stream(
        self, query: str, k: int = 5, min_score: float = 0.3
    ) -> Generator[str, None, None]:
        """
        Query with streaming response - yields tokens as they're generated.

        Args:
            query: Question to answer
            k: Number of documents to retrieve
            min_score: Minimum relevance score

        Yields:
            Response tokens one at a time
        """
        # First, search the document store if available
        context = ""
        if self._document_store is not None:
            docs = self._document_store.search(query, top_k=k)
            if docs:
                context_parts = []
                for doc in docs:
                    # Include relevant chunks
                    for chunk in doc.chunks[:3]:
                        context_parts.append(chunk)
                context = "\n\n".join(context_parts)

        # Fall back to retriever if no document store or no results
        if not context:
            chunks = self.retriever.retrieve(
                query, top_k=k, sources=["Document", "Memory", "Knowledge"]
            )
            if not isinstance(chunks, list) or not chunks:
                try:
                    chunks = self.retriever.search(
                        query, k=k, sources=["Document", "Memory", "Knowledge"]
                    )
                except TypeError:
                    chunks = self.retriever.search(query, k=k)
            chunks = [c for c in chunks if c.score >= min_score]
            context = self._build_context(chunks)

        if not context:
            yield "I don't have enough information to answer that question."
            return

        # Stream from LLM
        if self.llm_provider == "ollama":
            yield from self._stream_ollama(query, context)
        else:
            # For non-streaming providers, yield the full response
            response = self._generate(query, context)
            yield response

    def _stream_ollama(self, prompt: str, context: str) -> Generator[str, None, None]:
        """Stream response from Ollama."""
        import requests

        system = """You are a helpful assistant. Answer based on the provided context.
If the context doesn't contain relevant information, say so.
Be concise and accurate. Cite sources when possible."""

        full_prompt = f"""Context:
{context}

Question: {prompt}

Answer:"""

        response = requests.post(
            f"{self.llm_base_url}/api/generate",
            json={
                "model": self.llm_model,
                "prompt": full_prompt,
                "system": system,
                "stream": True,
                "options": {"temperature": 0.3},
            },
            stream=True,
            timeout=self.timeout,
        )
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                data = json.loads(line)
                if "response" in data:
                    yield data["response"]
                if data.get("done", False):
                    break

    def close(self):
        """Close connections."""
        self.retriever.close()

    async def ingest(self, path: str) -> IngestResult:
        """
        Ingest all supported documents from a directory.

        Args:
            path: Directory containing documents to ingest
        """

        return await asyncio.to_thread(self._ingest_directory_sync, path)

    async def ingest_documents(self, documents: list["Document"]) -> IngestResult:
        """
        Ingest pre-created Document objects.

        Args:
            documents: List of Document instances to persist
        """

        return await asyncio.to_thread(self._ingest_documents_sync, documents)

    def _require_document_store(self) -> "DocumentStore":
        if self._document_store is None:
            raise RuntimeError(
                "No document store configured. Pass document_store to RAGPipeline constructor."
            )
        return self._document_store

    def _create_loader_instance(self, loader_key: str, base_path: Path) -> "BaseLoader":
        base_dir = str(base_path)
        try:
            if loader_key == "text":
                from .loaders.text import TextLoader

                loader: BaseLoader = TextLoader(base_path=base_dir)
            elif loader_key == "markdown":
                from .loaders.text import MarkdownLoader

                loader = MarkdownLoader(base_path=base_dir)
            elif loader_key == "json":
                from .loaders.json_loader import JSONLoader

                loader = JSONLoader(base_path=base_dir)
            elif loader_key == "jsonl":
                from .loaders.json_loader import JSONLLoader

                loader = JSONLLoader(base_path=base_dir)
            elif loader_key == "csv":
                from .loaders.csv_loader import CSVLoader

                loader = CSVLoader(base_path=base_dir)
            elif loader_key == "excel":
                from .loaders.csv_loader import ExcelLoader

                loader = ExcelLoader(base_path=base_dir)
            elif loader_key == "pdf":
                from .loaders.pdf import PDFLoader

                loader = PDFLoader(base_path=base_dir)
            elif loader_key == "docx":
                from .loaders.docx import DocxLoader

                loader = DocxLoader(base_path=base_dir)
            elif loader_key == "html":
                from .loaders.html import HTMLLoader

                loader = HTMLLoader(base_path=base_dir)
            else:
                raise ValueError(f"Unsupported loader: {loader_key}")
        except ImportError as exc:  # pragma: no cover - optional deps
            raise RuntimeError(f"Loader '{loader_key}' is unavailable: {exc}") from exc

        with suppress(Exception):
            loader.authenticate()
        return loader

    def _ingest_directory_sync(self, path: str) -> IngestResult:
        store = self._require_document_store()
        start = time.perf_counter()
        errors: list[str] = []
        documents_processed = 0
        chunks_created = 0

        base_path = Path(path).expanduser()
        if not base_path.exists():
            errors.append(f"Path not found: {base_path}")
            duration = time.perf_counter() - start
            return IngestResult(documents_processed, chunks_created, errors, duration)

        if not base_path.is_dir():
            errors.append(f"Not a directory: {base_path}")
            duration = time.perf_counter() - start
            return IngestResult(documents_processed, chunks_created, errors, duration)

        loader_cache: dict[str, BaseLoader] = {}

        try:
            files = sorted(p for p in base_path.rglob("*") if p.is_file())
        except Exception as exc:
            errors.append(f"Failed to scan {base_path}: {exc}")
            duration = time.perf_counter() - start
            return IngestResult(documents_processed, chunks_created, errors, duration)

        for file_path in files:
            ext = file_path.suffix.lower()
            loader_key = LOCAL_EXTENSION_LOADERS.get(ext)
            if not loader_key:
                continue

            try:
                loader = loader_cache.get(loader_key)
                if loader is None:
                    loader = self._create_loader_instance(loader_key, base_path)
                    loader_cache[loader_key] = loader
                loaded_doc = loader.load_document(str(file_path))
            except Exception as exc:
                errors.append(f"{file_path.name}: {exc}")
                continue

            if not loaded_doc or not loaded_doc.content:
                errors.append(f"{file_path.name}: empty or unsupported document")
                continue

            metadata = dict(getattr(loaded_doc, "metadata", {}) or {})
            metadata.setdefault("source", getattr(loaded_doc, "source", loader_key))
            metadata.setdefault(
                "source_id", getattr(loaded_doc, "source_id", str(file_path))
            )
            metadata.setdefault(
                "filename", getattr(loaded_doc, "filename", file_path.name)
            )
            metadata.setdefault("mime_type", getattr(loaded_doc, "mime_type", ""))

            try:
                stored_doc = store.add(loaded_doc.content, metadata=metadata)
                documents_processed += 1
                chunks_created += len(stored_doc.chunks)
            except Exception as exc:
                errors.append(f"{file_path.name}: {exc}")

        for loader in loader_cache.values():
            with suppress(Exception):
                loader.close()

        duration = time.perf_counter() - start
        return IngestResult(documents_processed, chunks_created, errors, duration)

    def _ingest_documents_sync(self, documents: list["Document"]) -> IngestResult:
        store = self._require_document_store()
        start = time.perf_counter()
        errors: list[str] = []
        documents_processed = 0
        chunks_created = 0

        for document in documents:
            try:
                stored_doc = store.add(document)
                documents_processed += 1
                chunks_created += len(stored_doc.chunks)
            except Exception as exc:
                doc_id = getattr(document, "id", "unknown")
                errors.append(f"{doc_id}: {exc}")

        duration = time.perf_counter() - start
        return IngestResult(documents_processed, chunks_created, errors, duration)


# Convenience function
_default_pipeline: Optional[RAGPipeline] = None


def ask(query: str, k: int = 5, sources: Optional[list[str]] = None) -> str:
    """
    Quick RAG query - returns just the answer.

    Usage:
        from agentic_brain.rag import ask
        answer = ask("How do I deploy?")
    """
    global _default_pipeline

    if _default_pipeline is None:
        _default_pipeline = RAGPipeline()

    result = _default_pipeline.query(query, k=k, sources=sources)
    return result.answer
