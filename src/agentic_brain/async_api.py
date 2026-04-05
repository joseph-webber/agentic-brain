# SPDX-License-Identifier: Apache-2.0
"""
Async API compatibility layer for Agentic Brain.

Provides lightweight async wrappers around the existing synchronous
RAG pipeline, embedding providers and LLM access points. These helpers
make it easier to adopt asyncio without rewriting the full codebase.
"""
from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator, Iterable, List, Optional

from .rag.embeddings import EmbeddingProvider
from .rag.pipeline import RAGPipeline, RAGResult


class AsyncEmbedder:
    """Async wrapper around an EmbeddingProvider.

    Usage:
        embedder = AsyncEmbedder(sync_embedder)
        vec = await embedder.embed("hello")
    """

    def __init__(self, embedder: EmbeddingProvider):
        self._embedder = embedder

    async def aembed(self, text: str) -> List[float]:
        return await asyncio.to_thread(self._embedder.embed, text)

    async def aembed_batch(self, texts: Iterable[str]) -> List[List[float]]:
        return await asyncio.to_thread(self._embedder.embed_batch, list(texts))


class AsyncLLM:
    """Async wrapper for simple LLM generator functions.

    The project has multiple LLM call sites (ollama, openai); this wrapper
    allows using generate() in async code by delegating to a sync callable.
    """

    def __init__(self, generate_callable: Any):
        """generate_callable(prompt, context) -> str"""
        self._gen = generate_callable

    async def agenerate(self, prompt: str, context: str) -> str:
        # Call the generator/creator in a thread and consume it there so we don't
        # accidentally return a generator object to the caller. Some providers
        # yield tokens (generators) while others return a final string.
        def _call_and_consume():
            result = self._gen(prompt, context)
            # If the callable produced a generator (streaming), consume it fully
            if hasattr(result, "__iter__") and not isinstance(result, (str, bytes)):
                collected = []
                try:
                    while True:
                        token = next(result)
                        collected.append(str(token))
                except StopIteration as e:
                    # Python 3.3+: generator can return a value via StopIteration.value
                    if hasattr(e, "value") and e.value is not None:
                        return str(e.value)
                return "".join(collected)
            return result

        return await asyncio.to_thread(_call_and_consume)

    async def astream(self, prompt: str, context: str) -> AsyncGenerator[str, None]:
        """Wrap a blocking streaming generator into an async generator.

        If the underlying callable returns a generator, stream its tokens.
        If it returns a string, yield the string as a single token.
        """
        loop = asyncio.get_event_loop()
        q: asyncio.Queue = asyncio.Queue()

        def _produce():
            try:
                result = self._gen(prompt, context)
                if hasattr(result, "__iter__") and not isinstance(result, (str, bytes)):
                    try:
                        while True:
                            token = next(result)
                            loop.call_soon_threadsafe(q.put_nowait, token)
                    except StopIteration:
                        # Ignore explicit generator return value for streaming
                        pass
                else:
                    loop.call_soon_threadsafe(q.put_nowait, result)
            finally:
                loop.call_soon_threadsafe(q.put_nowait, None)

        import threading

        t = threading.Thread(target=_produce, daemon=True)
        t.start()

        while True:
            item = await q.get()
            if item is None:
                break
            yield item


class AsyncGraphClient:
    """Async-friendly thin wrapper around graph retrievers.

    It accepts any object exposing a ``retrieve`` method (blocking) and
    exposes an async ``aretrieve`` coroutine.
    """

    def __init__(self, client: Any):
        self._client = client

    async def aretrieve(self, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self._client.retrieve, *args, **kwargs)

    async def aclose(self) -> None:
        if hasattr(self._client, "close"):
            await asyncio.to_thread(self._client.close)


class AsyncRAGPipeline:
    """Async wrapper around RAGPipeline.

    This class demonstrates a non-invasive approach to adding async/await
    support: it runs existing sync code in threadpool workers and exposes
    async-friendly methods. It also demonstrates simple parallelism using
    asyncio.gather where it makes sense.
    """

    def __init__(
        self,
        pipeline: Optional[RAGPipeline] = None,
    ) -> None:
        self.pipeline = pipeline or RAGPipeline()
        # Some test harnesses provide a lightweight pipeline stub without a
        # full embeddings provider. Be tolerant and provide a tiny fallback
        # embedder when needed.
        embedder_src = getattr(self.pipeline.retriever, "embeddings", None)
        if embedder_src is None:

            class _FallbackEmbedder:
                def embed(self, text: str):
                    return [float(len(text))]

                def embed_batch(self, texts):
                    return [[float(len(t))] for t in texts]

            embedder_src = _FallbackEmbedder()

        self._embedder = AsyncEmbedder(embedder_src)
        self._llm = AsyncLLM(self.pipeline._generate)
        self.graph = AsyncGraphClient(self.pipeline.retriever)

    async def aquery(
        self,
        query: str,
        k: int = 5,
        sources: Optional[List[str]] = None,
        use_cache: bool = True,
        min_score: float = 0.3,
    ) -> RAGResult:
        """Async query that parallelises retrieval

        It performs two complementary retrieval calls in parallel (when available)
        and then generates an answer using the LLM in a thread. This is a best-effort
        concurrency improvement without touching blocking libraries directly.
        """
        # Schedule two retrieval strategies in parallel to reduce latency when both are available
        retrieve_task = asyncio.to_thread(
            self.pipeline.retriever.retrieve,
            query,
            top_k=k,
            sources=sources or ["Document", "Memory", "Knowledge"],
        )
        search_task = asyncio.to_thread(
            self.pipeline.retriever.search,
            query,
            k=k,
            sources=sources or ["Document", "Memory", "Knowledge"],
        )
        try:
            retrieved, searched = await asyncio.gather(retrieve_task, search_task)
        except Exception:
            # Fall back to single retrieval
            retrieved = await asyncio.to_thread(
                self.pipeline.retriever.retrieve, query, top_k=k
            )
            searched = []

        # Combine and de-duplicate by content
        chunks = []
        seen = set()
        for c in (retrieved or []) + (searched or []):
            key = getattr(c, "content", None) or str(getattr(c, "source", "")) + str(
                getattr(c, "score", "")
            )
            if key in seen:
                continue
            seen.add(key)
            if getattr(c, "score", 1.0) >= min_score:
                chunks.append(c)

        # Build context in thread
        context = await asyncio.to_thread(self.pipeline._build_context, chunks)

        if not context:
            answer = "I don't have enough information to answer that question."
            confidence = 0.0
        else:
            answer = await self._llm.agenerate(query, context)
            confidence = (
                sum(getattr(c, "score", 0.0) for c in chunks) / len(chunks)
                if chunks
                else 0.0
            )

        return RAGResult(
            query=query,
            answer=answer,
            sources=chunks,
            confidence=confidence,
            model=f"async/{self.pipeline.llm_provider}/{self.pipeline.llm_model}",
        )

    async def aquery_stream(
        self, query: str, k: int = 5, min_score: float = 0.3
    ) -> AsyncGenerator[str, None]:
        """Async streaming generator that forwards tokens from the underlying pipeline."""
        # Use the pipeline's query_stream via AsyncLLM.stream wrapper where possible
        # Fall back to running the blocking generator in a thread.
        stream = self.pipeline.query_stream
        loop = asyncio.get_event_loop()
        q: asyncio.Queue = asyncio.Queue()

        def _producer():
            try:
                for token in stream(query, k=k, min_score=min_score):
                    loop.call_soon_threadsafe(q.put_nowait, token)
            finally:
                loop.call_soon_threadsafe(q.put_nowait, None)

        import threading

        t = threading.Thread(target=_producer, daemon=True)
        t.start()

        while True:
            item = await q.get()
            if item is None:
                break
            yield item

    async def ingest_documents_parallel(self, documents: list[Any]) -> Any:
        """Example helper that ingests documents concurrently using asyncio.gather.

        This demonstrates using asyncio.gather to run many blocking store operations
        in parallel using the default ThreadPoolExecutor.
        """
        # Try to obtain a real document store; fall back to a dummy one that
        # raises so callers receive exceptions when no store is present.
        store = None
        try:
            if hasattr(self.pipeline, "_require_document_store"):
                store = self.pipeline._require_document_store()
        except Exception:
            store = None

        if store is None:

            class _NoStore:
                def add(self, doc):
                    raise RuntimeError("no document store configured")

            store = _NoStore()

        async def _add(doc):
            return await asyncio.to_thread(store.add, doc)

        tasks = [_add(doc) for doc in documents]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

    async def aclose(self) -> None:
        await asyncio.to_thread(self.pipeline.close)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.aclose()
