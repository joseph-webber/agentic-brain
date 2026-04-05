"""Batch helpers for embeddings and Neo4j queries."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Iterable, Sequence, TypeVar

T = TypeVar("T")
R = TypeVar("R")


def _chunked(items: Sequence[T], batch_size: int) -> list[list[T]]:
    return [list(items[i : i + batch_size]) for i in range(0, len(items), batch_size)]


@dataclass
class BatchResult:
    items: list[Any]
    batch_count: int


class BatchEmbeddingProcessor:
    """Generate embeddings in batches."""

    def __init__(self, provider: Any, batch_size: int = 32) -> None:
        self.provider = provider
        self.batch_size = batch_size

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if hasattr(self.provider, "embed_batch"):
            return self.provider.embed_batch(texts)

        result: list[list[float]] = []
        for batch in _chunked(texts, self.batch_size):
            result.extend(self.provider.embed(text) for text in batch)
        return result

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if hasattr(self.provider, "embed_batch"):
            maybe = self.provider.embed_batch(texts)
            return await maybe if inspect.isawaitable(maybe) else maybe

        tasks = [asyncio.to_thread(self.provider.embed, text) for text in texts]
        return list(await asyncio.gather(*tasks))


class BatchGraphQueryProcessor:
    """Execute graph queries in batches."""

    def __init__(
        self, query_fn: Callable[[list[str]], Any], batch_size: int = 32
    ) -> None:
        self.query_fn = query_fn
        self.batch_size = batch_size

    def execute(self, queries: list[str]) -> list[Any]:
        results: list[Any] = []
        for batch in _chunked(queries, self.batch_size):
            results.extend(self.query_fn(batch))
        return results

    async def aexecute(self, queries: list[str]) -> list[Any]:
        results: list[Any] = []
        for batch in _chunked(queries, self.batch_size):
            batch_result = self.query_fn(batch)
            if inspect.isawaitable(batch_result):
                batch_result = await batch_result
            results.extend(batch_result)
        return results


class AsyncBatchProcessor:
    """Process items asynchronously with bounded concurrency."""

    def __init__(self, concurrency: int = 8, batch_size: int = 32) -> None:
        self.concurrency = concurrency
        self.batch_size = batch_size

    async def process(
        self,
        items: Iterable[T],
        worker: Callable[[T], Awaitable[R] | R],
    ) -> list[R]:
        semaphore = asyncio.Semaphore(self.concurrency)

        async def run(item: T) -> R:
            async with semaphore:
                result = worker(item)
                if inspect.isawaitable(result):
                    return await result
                return result

        results: list[R] = []
        item_list = list(items)
        for batch in _chunked(item_list, self.batch_size):
            tasks = [asyncio.create_task(run(item)) for item in batch]
            results.extend(list(await asyncio.gather(*tasks)))
        return results


def batch_graph_queries(
    queries: list[str],
    query_fn: Callable[[list[str]], Any],
    batch_size: int = 32,
) -> list[Any]:
    return BatchGraphQueryProcessor(query_fn, batch_size=batch_size).execute(queries)


async def async_batch_process(
    items: Iterable[T],
    worker: Callable[[T], Awaitable[R] | R],
    *,
    concurrency: int = 8,
    batch_size: int = 32,
) -> list[R]:
    return await AsyncBatchProcessor(
        concurrency=concurrency,
        batch_size=batch_size,
    ).process(items, worker)
