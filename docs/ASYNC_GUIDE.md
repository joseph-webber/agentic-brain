Async Support Guide

This document describes the new lightweight async compatibility layer.

Overview

- src/agentic_brain/async_api.py contains:
  - AsyncRAGPipeline: async-friendly wrapper around existing RAGPipeline
  - AsyncGraphClient: async wrapper around retriever/graph client
  - AsyncEmbedder: async wrapper around embedding providers
  - AsyncLLM: async wrapper for LLM generate and streaming

Design notes

- The wrappers use asyncio.to_thread to run existing blocking code in threadpool workers.
- Async streaming is implemented by running blocking generators in a background thread
  and forwarding tokens via asyncio.Queue to the async caller.
- asyncio.gather is used in examples (AsyncRAGPipeline.aquery and ingest_documents_parallel)
  to parallelise retrieval / store operations without modifying synchronous libraries.

Usage

    from agentic_brain.async_api import AsyncRAGPipeline

    async with AsyncRAGPipeline() as api:
        result = await api.aquery("What is the status of project X?")
        async for token in api.aquery_stream("Explain project X"):
            print(token)

Testing

- Unit tests for async wrappers live under tests/test_async/ and are executed with pytest.

Limitations

- This layer is intentionally non-invasive: it does not replace synchronous
  implementations with full async equivalents. For best performance, asynchronous
  drivers (aiohttp, native async DB drivers) should be adopted in place of blocking
  libraries.

