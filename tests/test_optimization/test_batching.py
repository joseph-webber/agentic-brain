"""Performance-oriented tests for batching helpers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from agentic_brain.optimization.batching import (
    AsyncBatchProcessor,
    BatchEmbeddingProcessor,
    BatchGraphQueryProcessor,
    async_batch_process,
    batch_graph_queries,
)


@dataclass
class BatchEmbeddingProvider:
    batch_calls: int = 0
    single_calls: int = 0

    def embed(self, text: str) -> list[float]:
        self.single_calls += 1
        return [float(len(text))]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.batch_calls += 1
        return [[float(len(text))] for text in texts]


def test_batch_embedding_processor_uses_batch_api():
    provider = BatchEmbeddingProvider()
    processor = BatchEmbeddingProcessor(provider, batch_size=2)

    result = processor.embed(["a", "bb", "ccc"])

    assert result == [[1.0], [2.0], [3.0]]
    assert provider.batch_calls == 1
    assert provider.single_calls == 0


def test_batch_embedding_processor_falls_back_to_singles():
    class NoBatchProvider:
        def __init__(self) -> None:
            self.calls = 0

        def embed(self, text: str) -> list[float]:
            self.calls += 1
            return [float(len(text))]

    provider = NoBatchProvider()
    processor = BatchEmbeddingProcessor(provider, batch_size=2)

    result = processor.embed(["a", "bb", "ccc"])

    assert result == [[1.0], [2.0], [3.0]]
    assert provider.calls == 3


@pytest.mark.asyncio
async def test_batch_embedding_processor_async_uses_batch_api():
    provider = BatchEmbeddingProvider()
    processor = BatchEmbeddingProcessor(provider, batch_size=2)

    result = await processor.aembed(["a", "bb", "ccc"])

    assert result == [[1.0], [2.0], [3.0]]
    assert provider.batch_calls == 1


def test_batch_graph_query_processor_batches_queries():
    batches: list[list[str]] = []

    def query_fn(batch: list[str]) -> list[dict[str, Any]]:
        batches.append(batch)
        return [{"query": query} for query in batch]

    processor = BatchGraphQueryProcessor(query_fn, batch_size=2)
    result = processor.execute(["q1", "q2", "q3"])

    assert result == [{"query": "q1"}, {"query": "q2"}, {"query": "q3"}]
    assert batches == [["q1", "q2"], ["q3"]]


@pytest.mark.asyncio
async def test_batch_graph_query_processor_async_batches_queries():
    batches: list[list[str]] = []

    async def query_fn(batch: list[str]) -> list[dict[str, Any]]:
        batches.append(batch)
        return [{"query": query} for query in batch]

    processor = BatchGraphQueryProcessor(query_fn, batch_size=2)
    result = await processor.aexecute(["q1", "q2", "q3"])

    assert result == [{"query": "q1"}, {"query": "q2"}, {"query": "q3"}]
    assert batches == [["q1", "q2"], ["q3"]]


def test_batch_graph_queries_helper():
    def query_fn(batch: list[str]) -> list[int]:
        return [len(query) for query in batch]

    assert batch_graph_queries(["a", "bb", "ccc"], query_fn, batch_size=2) == [1, 2, 3]


@pytest.mark.asyncio
async def test_async_batch_processor_handles_sync_workers():
    processor = AsyncBatchProcessor(concurrency=2, batch_size=2)
    result = await processor.process([1, 2, 3], lambda value: value * 2)

    assert result == [2, 4, 6]


@pytest.mark.asyncio
async def test_async_batch_process_helper():
    result = await async_batch_process(
        [1, 2, 3], lambda value: value + 1, concurrency=2
    )

    assert result == [2, 3, 4]


@pytest.mark.asyncio
async def test_async_batch_processor_limits_concurrency():
    processor = AsyncBatchProcessor(concurrency=2, batch_size=4)
    active = 0
    peak = 0
    lock = asyncio.Lock()

    async def worker(value: int) -> int:
        nonlocal active, peak
        async with lock:
            active += 1
            peak = max(peak, active)
        await asyncio.sleep(0.01)
        async with lock:
            active -= 1
        return value

    result = await processor.process([1, 2, 3, 4], worker)

    assert result == [1, 2, 3, 4]
    assert peak <= 2


@pytest.mark.asyncio
async def test_async_batch_processor_preserves_order():
    processor = AsyncBatchProcessor(concurrency=3, batch_size=3)

    async def worker(value: int) -> int:
        await asyncio.sleep(0.005 * (4 - value))
        return value

    result = await processor.process([1, 2, 3], worker)

    assert result == [1, 2, 3]


def test_batch_embedding_processor_empty_input():
    provider = BatchEmbeddingProvider()
    processor = BatchEmbeddingProcessor(provider)

    assert processor.embed([]) == []
